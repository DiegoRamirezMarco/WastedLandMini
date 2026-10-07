# Sounds

The game makes its own effects: short synthesised sounds, written by `python -m tools.make_art`
into `assets/sounds/`. It comes with no ambience and no music. Sound that goes on and on was
tried synthesised and taken out for being unbearable: it is only heard from a file put here.

A sound of your own goes here. Any file in this folder with the name of one of the game's is
played in its place: `hammer.wav` here is what is heard when somebody builds. Ambience goes in
`ambience/`, and is silent until there is a file for it. An effect that is missing is the
game's own, as it always was.

- `.wav` or `.ogg`. A `.wav` is taken before an `.ogg` of the same name.
- Any length and any sample rate. An effect is best kept under a second. Ambience is played
  round and round, so its end has to run into its beginning.
- How loud each kind is heard, and what plays when, is in `data/audio.json`: `events` for what
  happens, `actions` for what somebody in view is doing, `interface` for the player's own
  clicks, `ambience` for the air, and `volumes`. A new name there needs a file of that name,
  here or in `assets/sounds/`.
- A file that cannot be read is left out, and the game goes on without it.

## Effects

| File | Heard for |
|---|---|
| `alert` | events: caught_out, child_alone, couple_in_trouble, crisis_opened, feelings_stirring, fight_brewing … |
| `argument` | events: argument_started |
| `ask` | events: confession_started, government_proposed, material_wanted, proposal_started, research_waiting, sale_proposed … |
| `ballots` | events: vote_held |
| `banished` | events: resident_expelled |
| `bell` | events: merchant_arrived, merchant_left |
| `breach` | events: law_broken |
| `built` | events: site_finished |
| `chat` | events: chat_started, friendship_changed, heart_to_heart_started, taste_reaction |
| `clank` | events: item_broke, salvage_started; while somebody in view does: salvage |
| `click` | events: expedition_left, night_watch, research_chosen, stayed_in, work_started |
| `coins` | events: currency_named, item_bought, item_sold, keep_paid, loan_made, loan_repaid … |
| `cough` | events: dependence_began |
| `cradle` | events: child_born, child_taken_in |
| `crash` | events: object_salvaged, site_cancelled |
| `decree` | events: government_changed, law_enacted |
| `eat` | events: meal_started |
| `fanfare` | events: election_held, government_chosen, leader_chosen, tutorial_finished |
| `found_out` | events: taste_found_out |
| `gavel` | events: election_called, government_choosing, proposal_raised |
| `gift` | events: birthday, child_grew, gift_given, item_returned |
| `gulp` | events: drink_stood |
| `gust` | events: resident_left, weather_changed |
| `hammer` | events: build_started; while somebody in view does: build |
| `haul` | while somebody in view does: carry |
| `heartbreak` | events: breakup_started, confession_rejected, couple_broke_up, family_parted |
| `held` | events: resident_held |
| `hurt` | events: injured, limb_lost, privation |
| `knock` | events: stranger_at_gate |
| `learned` | events: research_finished |
| `mend` | while somebody in view does: repair |
| `missing` | events: food_spoiled, leader_seat_empty, no_food, no_medicine, no_water, post_vacant … |
| `order` | events: order_given, salvage_ordered; the player: order |
| `outcry` | events: fraud_claimed |
| `passed` | events: council_seated, proposal_accepted, proposal_changed, trade_terms_changed |
| `plot` | events: election_rigged |
| `pour` | events: dose_given |
| `power_down` | events: power_failed |
| `punch` | events: fight_started; while somebody in view does: fight |
| `refuse` | events: loan_overdue, proposal_dropped, swap_refused, trade_refused, wages_unpaid |
| `resolve` | events: crisis_resolved, dependence_passed, job_changed, law_repealed, raid_repelled, supply_restored … |
| `scrap` | events: item_scrapped |
| `siren` | events: raiders_at_gate |
| `site` | events: site_laid |
| `smoke` | events: substance_taken |
| `snore` | events: slept_rough |
| `static` | events: radio_bulletin |
| `supplies` | events: expedition_returned, goods_left, supplies_arrived |
| `swap` | events: item_swapped, trade_made |
| `theft` | events: raid, theft_committed |
| `toll` | events: child_died, death, leader_lost |
| `turned_down` | events: council_seat_left, leader_resigned, proposal_rejected, proposal_vetoed, trade_terms_kept |
| `ui_click` | the player: click |
| `ui_close` | the player: close |
| `ui_open` | the player: open |
| `ui_refuse` | the player: refuse |
| `ui_select` | the player: select |
| `wedding` | events: couple_formed, couple_married |
| `welcome` | events: newcomer_joined, resident_founded |
| `whisper` | events: affair, candidate_backed, kin_together, proposal_lobbied, rumor_told, tryst_started |

## Ambience

None of these comes with the game. Each is heard only once there is a file of that name in
`ambience/`, played round and round and coming up and dying away by itself.

| File | Heard |
|---|---|
| `ambience/wind` | by day |
| `ambience/night` | at night |
| `ambience/storm` | in a storm |
| `ambience/fire` | while a campfire is in view |
| `ambience/generator` | while a generator is in view and there is power |
| `ambience/voices` | while people in view talk |
