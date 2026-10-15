# THE UNIVERSE — database → decomposition → generation (owner vision, 2026-10-15)

Three-stage flywheel, each stage feeding the next:

## Stage 1 — The Database (every comedian)
- **Standupedia**: 7,142 comedians, 107 countries, style tags
  ("absurdist · self-deprecating" = comedy types) — the backbone
- **killtonyarchive**: 2,046 KT sets, timestamps + crowd labels
  (silence→roaring) + topics + scores (`kt_archive_graph.py` — first
  45 episodes in: 569 sets, 408 comedians)
- killtonywiki (4,604 comedians), Scraps-from-the-Loft (599 full
  specials), StandUp4AI (3,617 videos, laughter-labeled), Kaggle sets
- OUR LAYER: kgraphs + delivery states + voice cards + stencils for
  the performers we've calibrated (ari/casey/pickles/kam/louis/norm/will)

## Stage 2 — Decomposition (why funny) → THE YOUTUBE CHANNEL
Per set, the pipeline already runs:
`breakdown.py` → dpv numbers + beat-by-beat theory tags (garden_path,
identity_contradiction, surprise, escalation) + laugh timeline + the
LOUIS-JOKE-ANATOMY template → markdown, narration-ready.
Channel format: one video per set/breakdown; voice-over from our engine;
captions via render.py; laugh moments from laugh_sim/am events. At scale:
536 KT episodes x ~13 sets = ~7,000 breakdowns; Standupedia expands to
non-KT. The channel IS the decomposition pipeline, published.

## Stage 3 — Generation (funny AI comedians)
Every decomposition feeds the generation engine:
- stencils (delivery) + collision shapes (theory) + voice cards +
  character graphs (identity gap) + crowd sim + judge
- `show_runner` episodes = the comedians performing; `laugh_sim` = the
  audience; `laugh_predictor` = the compass; ledger = the memory
- at scale: per-archetype material from decomposed collision shapes
  (the counterpoint/micro-surprise structures mined per set), matched
  to character graphs, rendered through proven delivery states

## The loop
database → decompose (channel grows the audience + the data) →
generate (AI comedians) → audience sim/judge → real ratings →
back into profiles. The channel monetizes stage 2 while stage 3 trains.
