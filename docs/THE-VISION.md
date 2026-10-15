# THE VISION (owner, verbatim, 2026-10-15)

> i basically want a huge database of comedians, then expanding to their
> sets decomposing with comedy theory and research then from all of it we
> basically now have a universe we can repeat all these pipelines at
> scale, automate a youtube channel breaking down why something is funny
> and then from all this data producing funny ai comedians

Addendum (2026-10-16):

> the whole thing going forward is expanding what comedy means to ai

Operational reading (not owner words): the three-stage flywheel lives in
`docs/UNIVERSE.md`. The ranking product: shortform minutes (45–100s),
blind A/B voting, objective leaderboard — finding the funniest minute in
existence. See `minute_battle.py`.

Addendum 2 (2026-10-15) — the stand-still lane:

> these 3 comics [norm, seinfeld, louis] we can get a jev classifier for
> each also their delivery and train it on their data and then
> potentially from that be able to generate a new minute that is similar
> to them, this is where our joke blocks come into play its simply
> taking the recipe of the comedian and applying it to a controversial
> thing

Pipeline: per-comedian labeled beats → delivery classifier (Jev state
with their examples / sklearn on their GT) → recipe = emotion arc +
timing + technique weights (louis: literalize .24, escalate .19,
self-pay .16) → joke block = current-events/controversial material
aimed through THEIR collision shape → rendered minute in their clone.
The recipe transfers; the topic rotates.
