# HANDOVER — prx0r/characters (2026-10-15)

Read in order: `docs/THE-VISION.md` (owner, verbatim) → `AGENTS.md`
(hard rules + how every pipeline works) → `docs/ENGINE-MAP.md` (deep
file map) → this file (live state).

## Freak SDK pilot (2026-10-21, on box clone)
Character profiles carry `voice.tags` + `delivery.style` (SPEC-FREAK-SDK.md).
`audition/style_harvest.py` turns scribe clips into delivery_style.v1
(Louis self-test PASS); `delivery_engine.load_profile` reads freaks→styles
(first: buddha-ultimate-deadpan → norm_macdonald recipe + cast Fish voice
"Calm Monotone Narrator" 2821f84c…, all $0). Styles in `voicelab/styles/`.

**Attardo timing layer (same day):** `theory/attardo-timing-map.md` = the
ch10/GTVH claim → knob contract (T1-T12). Engine now: pre-punch hold BEFORE
punch audio (0.6s floor / character override), post_punch_s resolution
window merged via max() at assemble, p_laugh scales the window (audience
loop), Norrick speed contrast via BEAT_SPEED×MECH_SPEED decomposed by
tempo_via_prompt (clean-zone rule kept), style volume_db + temperature
actually reach the Fish call, [emphasis] on punch/closer except flat styles
(volume ≤ −2 = deadpan: unstressed words, manner-max flout). Buddha render
verified: holds 1.51–1.64s in audio, post windows 1.0–1.19s, word match
0.981. gcomedy graph nodes (KR-NS/prosody/timing/release) now map to the
SDK (gcomedy 367bc80). **Avatar mapping (same day):** `audition/seal_set.py`
(+ delivery_engine `--seal DIR`) exports sealed-set.v1 for freaktown
`loadSealedSet` — timeline with exact ms, energy-envelope mouth cues,
set_plan with character profile + per-beat performance (character actions
win: koan_hold → deadpan + hold → locomotion.freeze). `freaks/mesh-map.json`
= slug → their cast GLB families (zero name overlap; anansi→spider
confident, cryptids→monster/kappa→nature plausible, rest todo/appearance
fallback). Verified: their adaptSealedSet 5/5 (fixture on branch
freaktown `sdk-sealed-export`). Next: archetype pooling beyond norm,
human/deity mesh families, live POG loop, MCP wrapper.


## Hard rules (absolute, violations happened)
1. Synthesis = `s2.1-pro-free` ONLY ($0), ALWAYS. MCP TTS forbidden
   for renders (plan credits). MCP free = clones, search, balance.
2. Pitch-slide era OVER: no fish speed-knob outside 0.92–1.08 clean
   zone; no post-stretch code. Tempo = direction language only.
3. Never invent funny minutes. Sets lead: actual text + substitutions,
   or stencil mapping. Foundry/riffchain generators were DELETED.
4. Judge humility: calibration ladder garbage < generated < pro must
   hold (currently: louis-gen 0.868 > dracula 0.606 > soup 0.507 >
   flat-bomb 0.366). Real pros must outrank generated.
5. Ask before ANY spend with exact numbers. Keys in .env only (600).

## Focus roster (owner 2026-10-15)
**LOUIS, ARI, SEINFELD, NORM** — the stand-still GOATs (voice-first
tier). CASEY PARKED (too out there). Everything prioritizes these four.

## Live state
- **Clones (free MCP):** ari dbeb1d68, casey 9c36c951, pickles 100e10e7,
  louis fb015415, norm 085d6397, will 9c1e2194, kam 6ab05a97,
  seinfeld f73820b8. `clone_ids.json` (also inlined in jev_loop).
- **Delivery states converged:** ari (kt704), casey (set2), pickles
  (set1+2), kam (set1). Louis = formula-level (`LOUIS-FORMULA.md`).
  Seinfeld:5 clips ingested (cf_asr+AM-GT), registered in jev_loop,
  calibration loops NOT yet run (next task).
- **Identity judge** (`identity_judge.py`): per-comedian discriminator
  ("is this actually their set?"). Real-render baselines: casey ~0.42
  (consistent), louis-act 0.56/2.4. Target for generation loops: >0.8.
  What-breaks-it = material|delivery|structure (directed iteration).
- **Laugh sim** (`laugh_sim.py`): listens to any audio, mixes crowd at
  predicted moments. Precision ~60-78% where GT reliable. Free.
- **Minute battle** (:8809, `minute_battle.py`): blind A/B leaderboard,
  10 minutes seeded. Server may need restart: `python3 audition/
  minute_battle.py` (seeded data persists in minute_battle.json).
- **show_runner** + `voicelab/shows/`: episodes with simulated crowd +
  judge (real = measured density, gen = predicted).
- **Voice lab**:9 voice cards, 5 domain recipes, stencils for 10 sets,
  MARY affect model, emerge.py, kgraphs (sweetheart_dracula + 7 kgraphs).
- **Theory**: LAUGH-PHYSICS, DVP (pause ladder 0.6/1.5/1.0+jitter),
  LOUIS-FORMULA (1.67s pauses, confession-booth: literalize .24/
  escalate .19/self-pay .16), PHYSICALITY-AXIS, ENGINE-ARCHETYPE-MAP,
  LOUIS-JOKE-ANATOMY, RESEARCH-REVIEW. kt_archive_graph.json: 569 sets
  /408 comedians (name-noise cleanup pending).
- **Corpus**: scribes+GT for ari/casey/pickles/louis(13 clips)/will/kam/
  lazer/seinfeld(5). Casey riff_db 666 labeled riffs. Jev via
  OpenRouter (typesafe/jev-1.13, multimodal w/ danger-zone header).
- **Datasets archived**: /home/box/voice_engine/sets, /home/box/*.wav
  (battle entries, sims, mappings).

## Next steps (in order)
1. Seinfeld calibration loops (`jev_loop.py run --set seinfeld_c01..c05
   --rounds 4`) → converge his state; add style card to identity_judge.
2. Identity-judge calibration with more real sets (louis/norm/ari
   baselines); target: real renders >0.6, generated iterate to >0.8.
3. First joke-block demos: controversial topic × louis/ari/seinfeld
   recipes (collision shapes from ENGINE-ARCHETYPE-MAP); judge loop.
4. Norm: clips on box (norm_sets), needs scribe+GT (cf_asr pipeline
   proven) → state.
5. Standupedia scraper (style tags,7142 comedians) + kt_archive name
   cleanup → the database stage.
6. Channel: batch breakdown.py over archived sets; minute_battle
   ratings feed voice_battle taste weights.

## Gotchas
- Fish library voice IDs rot (narrator id died). Re-probe before use.
- CF whisper:429/408s → cf_asr falls back to local tiny (slow on long
  clips; prefer ≤150s windows).
- Jev predictions vary run to run; convergence claims need the bounds
  check in jev_loop, not vibes.
- The archive parser leaks label lines as comedian names (cleanup todo).
- beat scribe text includes [laughing] tokens — strip before rendering.
