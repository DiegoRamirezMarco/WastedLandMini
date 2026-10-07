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
| `resident_founded` | The player's first resident walks in | 45 |
| `tutorial_step_done` | A step of a new settlement's opening is done, with its ID in `data.step` | 35 |
| `tutorial_finished` | The last step is done, and the world outside stops keeping away | 45 |
| `activity_started` | A resident starts using an object | 5 |
| `meal_started` | A resident starts eating, with the food ID in `data.item_id` | 5 |
| `work_started` | A resident takes up their post | 5 |
| `goods_hauled` | A worker leaves a load in a container, or fetches one from it | 5 |
| `item_bought` | A resident buys something over the counter, with `item_id`, `price` and `for` (who it is a present for, or null) in `data`. From a merchant, `merchant` names the event that brought them | 15 |
| `item_swapped` | Under barter, a resident has something off the counter for a thing of their own, with `item_id` and `given_id` in `data` | 15 |
| `swap_refused` | Whoever keeps the counter will not have any of what a resident offers for a thing (once a day for each resident) | 20 |
| `keep_paid` | Under barter, someone the settlement no longer keeps hands a thing over for a meal, a drink or a repair, with `item_id` in `data` | 10 |
| `supply_cut`, `supply_restored` | The settlement stops keeping someone who has not worked for days, or takes them back | 40 |
| `drink_stood` | Someone pays for what a friend at the same bar could not | 15 |
| `loan_made`, `loan_repaid` | A resident lends another credit, or has it back, with `amount` in `data` | 20 |
| `loan_overdue` | A loan has gone unpaid long enough to tell on the two of them | 35 |
| `trade_raised` | A resident thinks of putting a currency, or going back to barter, to everyone, and waits for advice | 50 |
| `currency_named` | The player gives the currency its name, with `currency_id` in `data` | 30 |
| `wages_unpaid` | The fund has nothing left to pay a wage with (once a day) | 35 |
| `trade_proposed` | A resident is asked whether the settlement should trade with a currency, or go back to barter | 30 |
| `trade_terms_changed` | The residents take up a currency, or go back to barter, with `currency_id` in `data` (null for barter) | 60 |
| `trade_terms_kept` | They were asked and would rather go on as they are | 40 |
| `item_broke` | Something wears right out | 30 |
| `post_vacant` | A job has been short of people too long (once per vacancy) | 35 |
| `job_offered` | A resident is asked to take a vacant job and waits for advice | 50 |
| `job_changed` | A resident takes up a job | 40 |
| `research_chosen` | The player says what is to be worked out next, with `subject` in `data` | 20 |
| `research_waiting` | Somebody holds the post and nothing has been chosen, or what the subject studies is nowhere to be had (once a day each) | 30 |
| `research_finished` | A subject is known, with `subject` in `data` | 45 |
| `site_laid` | Somebody has agreed to build something and its ground is marked out, with `site_id` in `data` | 20 |
| `build_started` | A resident sets to work on a site, with `site_id` in `data` | 5 |
| `site_waiting` | A site cannot be got on with: nothing to build it with, or nobody holding the job it asks for (once a day) | 30 |
| `site_finished` | What was being built stands, with `site_id`, `entity_id`, `kind` and `what` in `data` | 35 |
| `site_cancelled` | A site is given up | 20 |
| `chat_started` | Two residents start a friendly chat | 10 |
| `argument_started` | Two residents start an argument | 35, plus up to 30 with the resentment between them, plus 15 if one went looking for the other |
| `heart_to_heart_started` | A resident talks things out after a crisis | 30 |
| `rumor_told` | A resident tells another about a fact | 15 |
| `supplies_arrived` | The day's supplies reach a container | 10 |
| `no_food` | Someone finds nothing to eat, there or anywhere else (once a day) | 40 |
| `no_water` | The same, with nothing to drink | 40 |
| `privation` | A resident falls ill of a need left at its worst: thirst or hunger | 60 |
| `power_failed` | Night falls and the generator has no fuel (once a day) | 25 |
| `dose_given` | Someone lying in care is given a unit of what that care uses up, with `item` in `data` | 10 |
| `no_medicine` | Someone is lying in care and there is none to give them (once a day) | 40 |
| `gift_given`, `trade_made` | Something changes hands after a friendly exchange | 20, 15 |
| `taste_reaction` | A resident takes a meal, a drink, a thing used or a present well or badly, with `resident_id`, `item_id`, `reaction` (`hated`, `disliked`, `liked`, `loved`), `how` and `giver_id` in `data`. Taking it as any other is not an event | 8 |
| `taste_found_out` | The player comes to suspect or to know a taste of a resident, with `resident_id`, `taste`, `state` and `leaning` in `data`. Never a number | 12 suspected, 22 known |
| `taste_mentioned` | A resident speaks of something they like or cannot stand, at the end of a friendly exchange | 10 |
| `trade_refused` | A resident will not take a thing in a swap because it is not to their liking (once a day between the two) | 12 |
| `theft_committed` | A resident takes someone else's thing or credit, or takes from what the settlement holds in common. For credit and the fund, `victim_id` (`@fund` for the settlement) and `amount` in `data` | 45, or 30 for a meal or a drink taken without leave |
| `substance_taken` | A resident takes a substance, with `item_id` and `route` in `data` | 10 |
| `substance_seen` | Others see it on them, or are reached by the smoke, with `item_id` and `sign` in `data`. They are its participants after whoever took it | 15 |
| `substance_tempted` | A resident about to start on something that hooks, to go back to it, or to go for a habit stops and waits for advice | 50 |
| `dependence_began`, `dependence_passed` | A resident comes to depend on something, or gets over it, with `item_id` in `data` | 55, 45 |
| `theft_noticed` | An owner sees that something of theirs is gone, or whoever keeps the counter that the fund is short | 40 |
| `item_returned` | A stolen thing, or stolen credit, is handed back | 25 |
| `crisis_opened` | A resident boils over and waits for advice | 50 to 69, by anger |
| `fight_brewing` | A resident squares up to another and waits for advice | 60 to 69 |
| `fight_started` | Two residents come to blows | 60, plus up to 20 with resentment, plus 15 |
| `injured` | A resident comes out of something hurt | 45 |
| `limb_lost` | A resident loses a limb to an injury, in place of `injured` | 85 |
| `death` | A resident dies | 95 |
| `birthday` | A resident is a year older, with `age` in `data` | 20 |
| `slept_rough` | Someone lies down on the ground for want of a bed | 15 |
| `proposal_stirring` | A resident wonders whether to ask their partner to marry them, and waits for advice | 55 |
| `proposal_started`, `couple_married`, `proposal_rejected` | One asks; the other says yes, or no | 50, 65, 45 |
| `child_conceived` | Someone is carrying a child, with `other` and `due_day` in `data`. Nobody in the settlement knows | 35 |
| `child_born` | A child is born, with `child_id`, `parents`, `sex` and `of_kin` (whether the parents are kin by blood) in `data` | 70 |
| `child_grew` | A child is ten, and a resident from now on, with `child_id` in `data` | 50 |
| `child_alone` | Someone is asked to take in a bundle nobody is seeing to, and waits for advice | 65 |
| `child_taken_in` | They do, with `child_id` in `data` | 65 |
| `child_died` | A bundle nobody looked after dies, with `child_id` in `data` | 90 |
| `government_choosing` | The settlement has grown to where it wants a government, with `until` and the `kinds` there are in `data` | 65 |
| `government_proposed` | The player puts one kind to everyone, with `government` in `data` | 40 |
| `government_chosen` | The residents settle on a kind, or the player gives them one, with `government`, how many `wanted` each and whether it was `imposed` in `data` | 75 |
| `government_changed` | A settlement that had one kind of government takes another, with `from`, `to` and whether it was `imposed` in `data` | 75 |
| `leader_chosen` | Somebody comes to lead, with their `role`, the `way` and, after a show of hands, their `backers` in `data` | 65 |
| `council_seated` | Seats on the council are filled, with the `role` and the whole `council` in `data` | 55 |
| `leader_lost` | Whoever led is dead or gone, with `resident_id`, `role` and `died` in `data` | 75 |
| `resign_stirring` | A leader wonders whether to step down, and waits for advice | 60 |
| `leader_resigned`, `council_seat_left` | Somebody steps down from leading, or from the council, with the `role` in `data` | 65 |
| `leader_seat_empty` | Nobody can be found for the leader's seat | 60 |
| `election_called`, `election_held` | A vote for a seat is called, with when it is held (`at`), and held, with the `winner`, whether they `kept` the seat, the `tally` as given out, whether it was `open`, and their `backers` after a show of hands | 50, 60 |
| `resident_held` | The player stops a resident, who stands and listens | 10 |
| `order_given` | The player tells a resident to do something, with the `kind` of thing and its `target` in `data` | 25 |
| `material_wanted` | Whoever sees to a site sits by it with nothing to build with, with `site_id`, what is `wanted` and what could be taken apart for it (`salvageable`) in `data`. Once a day for each site | 45 |
| `salvage_ordered`, `salvage_started` | A resident is told to take something apart, and gets to it, with `object_id` in `data` | 20, 5 |
| `object_salvaged` | It is taken apart and gone, with `object_id`, `kind`, `tile`, `item_id` and `units` in `data` | 30 |
| `scrap_proposed` | The owner of a thing is asked to have it broken up | 30 |
| `item_scrapped` | An item is broken up for scrap, with `item_id`, `units` and where it was left (`into`) in `data` | 20 |
| `proposal_raised` | Something is laid before those who decide, with `proposal`, `kind`, `by` (a resident, or `@player`), the `sponsor` who made it theirs, what it is about, `decides_at` and the `deciders` in `data` | 55 |
| `proposal_dropped` | Nobody who may propose makes it theirs, or it no longer makes sense when its time comes | 40 |
| `proposal_lobbied` | The player speaks to one of those who decide, with the `stance` and how they `took` it in `data` | 30 |
| `vote_held` | More than one decide a proposal, with how many said `yes`, `no` and neither (`abstain`), whether it was `open`, and after a show of hands each one's vote (`ballots`) in `data` | 55 |
| `proposal_accepted`, `proposal_changed`, `proposal_rejected`, `proposal_vetoed` | How it came out, with `proposal`, `kind`, `status`, `by`, the `degree` it passed at and what it was about in `data` | 65 |
| `law_enacted`, `law_repealed` | A law comes into force, with `law`, `degree`, `params` and `by` in `data`, or stops being one | 60, 50 |
| `law_broken` | A resident is seen to break a law, with `law` and `resident_id` in `data`. At most once a day for each resident and law | 35 |
| `saluted` | A resident greets whoever leads, as a law has it | 8 |
| `resident_expelled` | A resident is thrown out, with `resident_id` and `by` in `data`, and sets off for the gate | 80 |
| `resident_left` | They go through it for good, with `resident_id` and the `tile` in `data` | 70 |
| `rigging_stirring` | A leader about to lose a secret vote wonders whether to see to the count, and waits for advice | 65 |
| `election_rigged` | They do. Only whoever sees them knows | 70 |
| `fraud_claimed` | A loser says there was cheating, with the `winner` and whether the vote was `rigged` in `data` | 60 |
| `candidate_backed` | The player speaks to a resident for a candidate, with `candidate` and how they `took` it in `data` | 30 |
| `kin_together` | Two close kin are a couple, or go off alone together: once for the two of them, with nobody knowing of it but whoever sees them | 60 |
| `family_parted` | One of two who came to the gate together is let in and the other is not, with `left` in `data` | 60 |
| `friendship_changed` | What one resident feels for another grows into a friendship, or out of it | 25 |
| `feelings_stirring` | A resident wonders whether to tell someone what they feel, and waits for advice | 50 |
| `confession_started` | A resident tells another what they feel | 45 |
| `couple_formed` | The one told feels the same | 60 |
| `confession_rejected` | The one told does not | 45 |
| `tryst_started` | A couple go off alone | 40 |
| `affair` | Two residents go off alone behind a partner's back | 55 |
| `couple_in_trouble` | A resident wonders whether to leave their partner, and waits for advice | 55 to 69, by anger |
| `breakup_started` | A resident tells their partner it is over | 55 |
| `couple_broke_up` | The couple is over | 65 |
| `expedition_left` | A resident leaves the settlement to scavenge | 15 |
| `risky_find` | A resident out there comes on something that looks dangerous, and waits for advice | 50 |
| `expedition_returned` | A resident comes back with what they found, with `found` and `kept` (what they keep for themselves under barter, or null) in `data` | 30 |
| `stranger_at_gate` | Someone asks to be let in, and the guard waits for advice | 55 |
| `newcomer_joined` | A stranger is let in and stays | 60 |
| `stranger_turned_away` | A stranger is sent on their way | 40 |
| `stranger_unanswered` | Someone knocks and there is no gatekeeper to answer | 35 |
| `merchant_arrived` | A merchant stops by the gate to trade, with `event_id` and `goods` in `data`. It happens where they stand | 45 |
| `merchant_left` | They move on | 20 |
| `merchant_deal` | The player sells them what is nobody's and buys from them, with `sold`, `bought` and `paid` (out of the fund, or into it if negative) in `data` | 30 |
| `sale_proposed` | A resident is asked to sell a merchant a thing of their own | 30 |
| `item_sold` | They do, or sell or swap one of their own accord, with `item_id`, `for_item` and `price` in `data` | 25, or 15 of their own accord |
| `goods_left` | A world event of kind `stock` leaves things in a container for nothing | 30 |
| `weather_changed` | A storm rises, or passes | 45, 30 |
| `food_spoiled` | Vermin eat part of what is in the pantries | 45 |
| `radio_bulletin` | A resident is the first to hear on a radio what is on its way | 35 |
| `stayed_in` | A resident who knows a storm is coming does not leave on a trip (once a day) | 20 |
| `caught_out` | A storm rises while a resident is outside the settlement | 45 |
| `night_watch` | A guard who knows raiders are about takes up their post out of hours (once a night) | 25 |
| `raiders_at_gate` | Raiders reach a gate that is kept, and the guard waits for advice | 65 |
| `raid_repelled` | The guard stands their ground and the raiders leave | 70 |
| `raid` | Raiders walk in and take what they can | 75 |
| `crisis_resolved` | The resident decides what to do | Same as the crisis |

Every event carries its participants, its witnesses, the room it happened in (if any) and a
`timestamp` in game minutes. The HUD colours events by band and marks with `!` anyone waiting for advice and the
participants of an ongoing event of importance 50 or more. An event that important also drops
the game back to normal speed.

Events describe what is happening. Decisions describe how the player can influence it. Advice should usually modify the resident's decision inputs rather than directly commanding the outcome.

Events of politics are a `PoliticalEvent`, which is a `DomainEvent` that also says the kind of
`government` it happened under.

## Particulars

An event may carry `data`: plain values for whoever shows or sounds it. The simulation never reads
them back, and they are saved with the event.

| Event | `data` |
|---|---|
| `injured` | `amount` (the severity of the injury), `kind`, and `by` (who dealt it, or null) |
| `limb_lost` | The same, and `limb` (the ID of the limb) |
| `death` | `resident_id`, `tile` (where the body fell, or null beyond the fence), `by` and `lost_limbs` |
| `privation` | `kind` (the injury it is) and `need` (what brought it on) |
