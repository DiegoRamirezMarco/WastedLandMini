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
| `work_pushed` | A resident is told to push their post for what is left of their shift, with `resident_id`, `job` and `until` (the game minute it ends) in `data` | 20 |
| `work_accident` | A push ends badly, with `resident_id`, `job`, `mishap` (`hurt`, `tool` or `spoil`) and `units` lost in `data` | 45 |
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
| `item_improved` | A thing mended at a workshop that has been made better comes away a rarity rarer, with `item_id`, `definition_id` and the `level` it has now in `data` | 20 |
| `object_upgraded` | Something that stands has been made a level better, with `object_id`, its `kind`, the `level` it has now and its `rarity` in `data`. The site it was done at gives `site_laid` and `site_finished` as any does, with `kind` `upgrade` | 35 |
| `post_broke` | A post is worn out, or a push broke it: it stands idle until it is mended, with `object_id` and its `kind` in `data`. The site it is mended at gives `site_laid` and `site_finished`, with `kind` `repair` | 45 |
| `post_mended` | A post that had broken down works again, with `object_id` and its `kind` in `data` | 30 |
| `power_switched` | The player switches something that runs on current on or off, with `object_id` and `on` in `data` | 10 |
| `went_off` | Things have gone off this hour and are compost, with `items` in `data`: units by item ID. Once for all of them | 30 |
| `bed_dressed` | Compost has been put on a bed at the player's word, with `object_id` and `until`, the game minute it lasts to, in `data` | 20 |
| `power_shed` | More current is asked for than there is, and what was switched on last is switched off, with `object_id` and the `supply` there is in `data` | 25 |
| `store_full` | The stores have no room left for a resource (once a day for each), with `resource` and the `capacity` there is in `data` | 35 |
| `resource_low` | The settlement's books say that what there is of a resource will last fewer days than `low_days`, or that there is none and it is being used (on the hour, once a day for each), with `resource`, `stock` and `days_left` in `data` | 35 |
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
| `trade_level` | A resident reaches a level of their job, with `resident_id`, `job` and `level` in `data` | 40 |
| `discovery_made` | A level brings somebody something new that waits to be named, with `discovery`, `resident_id`, `job`, `kind` and `level` | 60 |
| `discovery_named` | The player says what it is, with `discovery`, `resident_id`, `kind`, `item`, `name` and `choices` | 55 |
| `trade_taught`, `trade_lost` | Somebody learns a thing from whoever knows it (`discovery`, `teacher`, `learner`), or the last who knew one is gone (`discovery`, `resident_id`, `item`) | 40, 50 |
| `thing_made` | A post that makes nothing of its own finishes one of what its worker has come to, with `item` and `container` | 10 |
| `attribute_grew` | Somebody comes to a whole point more of an attribute by using it, with `resident_id`, `attribute` and `level` in `data` | 20 |
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
| `resident_placed` | The player takes a resident up and puts them down somewhere else, with the `kind` of thing that comes of it (`stand`, `person`, `post`, `swap`, `use`, `sit`, `site` or `salvage`), its `target`, and the tiles they went `from` and `to` in `data`. What they are told for it follows as `order_given`, and a post that changes hands as `job_changed` | 10 |
| `bundle_handed` | The player puts a child's bundle in the arms of a resident, with `child_id` in `data` | 20 |
| `bundle_set_down` | The player lays a child's bundle down, with `child_id` and the `place` (`bed`, `surface` or `ground`) in `data` | 20 |
| `bundle_taken_up` | Whoever sees to a bundle the player laid down takes it up again, for its being the worse for it, with `child_id` in `data` | 20 |
| `order_given` | The player tells a resident to do something, with the `kind` of thing and its `target` in `data` | 25 |
| `order_queued`, `order_cancelled` | The same, told to somebody who is at something else they were told, so that it waits its turn; and one of them taken back. Each with `kind` and `target` in `data` | 10 |
| `order_dropped` | Something a resident was told cannot be done when its turn comes, and is let go, with `kind` and `target` in `data` | 15 |
| `will_changed` | A resident is told to do nothing of their own accord, or given their will back, with `free` in `data` | 20 |
| `leisure_started` | A resident sets about a pastime alone, with the `pastime` and how they take it (`reaction`, or nothing) in `data` | 6 |
| `leisure_declined` | Somebody asked to go on somewhere with another does not care to | 12 |
| `joke_started`, `hug_started`, `flirt_started`, `kiss_started`, `insult_started`, `cards_started`, `stories_started`, `dance_started`, `invite_drink_started` | Two residents start that exchange, as with any other in `data/social.json` | as the data says |
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
| `law_enacted`, `law_repealed` | A law comes into force, with `law`, `degree`, `params`, `by` and whether it was `imposed` in `data`, or stops being one | 60, 50 |
| `protest_called`, `protest_held`, `protest_won` | People go out to the square against a law, stand there for the day (with `days` and whether it was `harsh`), and are heard when it is done away with or made milder (`gone`). `law` and `who` in `data` | 45, 55, 60 |
| `law_broken` | A resident is seen to break a law, with `law` and `resident_id` in `data`. At most once a day for each resident and law | 35 |
| `saluted` | A resident greets whoever leads, as a law has it | 8 |
| `resident_expelled` | A resident is thrown out, with `resident_id` and `by` in `data`, and sets off for the gate | 80 |
| `resident_left` | They go through it for good, with `resident_id` and the `tile` in `data` | 70 |
| `accusation_weighed` | A resident who knows of something somebody did wonders whether to accuse them, and waits for advice | 55 |
| `trial_opened` | Somebody is accused, by a resident or by the player, with `trial_id`, `accused`, `accuser` and `offence` in `data` | 55 |
| `trial_step` | A trial moves on: `evidence`, `witnesses` or `defence` as `step` in `data`, with what came of it in its text | 35 |
| `trial_verdict` | Those who judge have said, with `verdict` (`guilty` or `innocent`), `guilty` and `judges` in `data` | 60 |
| `punishment_carried` | What the player said somebody is given is done, with `punishment`, `offence`, `harsh`, `public`, who was `present` and how each took it as `reactions` in `data` | 46 to 100, by its severity |
| `sentence_served` | Somebody has done their days locked up, their hours in the stocks or their days of work | 40 |
| `prisoner_unfed` | There was nothing to give a prisoner of what they are to be given. At most once a day for each | 45 |
| `exile_at_gate` | Somebody who was exiled is at the gate asking to come back, and whoever is there waits for advice | 65 |
| `exile_readmitted`, `exile_turned_away` | They are let back in, the same person they were, or sent on their way | 65, 50 |
| `exile_raid` | Somebody exiled who left with a grudge comes back with raiders, and a raid follows | 75 |
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
| `house_given` | The player says whose a building is, with `room`, `owners` and who had it `before` in `data`. Those who gain and lose it are its participants | 30 |
| `house_locked` | The door of a building that is somebody's is locked or left open again, with `room` and `locked` in `data` | 10 |
| `building_named` | A building is given a name of its own, or said to be for something, with `room` in `data` | 10 |
| `house_decorated` | An ornament is put in a building or taken out of it, or its floor or walls are changed, with `room` in `data` | 5 |
| `trespass` | Somebody goes into a house they had no business in, for what is there. The first participant is who went in and the rest are whoever lives there; `data` has `room` and `object`. It happens where they are, and is known as a fact | 35 |
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
