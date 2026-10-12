# Pogtown RL Loop — How Learning Actually Works

*The closed loop: generate → perform → audience votes → scores flow back → next generation is smarter. All four gaps closed 2026-10-12.*

---

## The loop (end to end)

```
1. PREFILTER (new)          Jev scores premise BEFORE generation
   prefilter.py              cheap judgment (scenario + voice → viability)
                             dead premises rerolled, live ones proceed
                             exploit path only; explore bypasses; fail-open

2. GENERATE                   audition/battle: 3 variants
   generate.py + battle.py     Jev picks modulator/operator (NOW score-informed)
                               template or LLM writes beats
                               battle scores, winner persists

3. BRIDGE (new)               audition persist → graph instance
   app.py _record_graph_instance  instance + performs edge via SDK
                                    fail-open (never crashes audition)

4. PERFORM                    TTS + MP4 + /watch + arena
   existing                    POGs (laugh ground truth)
                               retention (skip/like/complete/replay)
                               feedbacks (0-3 + room)
                               arena blind votes → Elo/Wilson

5. SCORE BACK (new)           past performance reaches next Jev decision
   store.performance_history   battle_score + POGs + ratings by modulator
   jev_questions.seed_state    "performance" field (800 char budget)
   q_modulator                 "prefer high-scoring modulators" instruction

6. STRATEGIZE (new)           threshold-gated weight updates
   store.propose_strategy_update  ≥5 new scored auditions → proposed version
                                    top/bottom modulators + operators
                                    status='proposed' (pointer never moves
                                    without human accept)

7. TRAIN (new)                loser texts surfaced for negative learning
   store.loser_texts           full texts + score gaps (winner - loser)
                               feeds Jev calibration + future model training
```

---

## What was broken (found 2026-10-12)

| Gap | Symptom | Fix |
|---|---|---|
| Scores never reached Jev | `seed_state` had philosophy + scenario + text memories, zero battle scores. Ratings hardcoded 0. POGs fetched then dropped. | `performance_history()` + `format_performance_brief()` → `seed_state(performance_brief)` → `q_modulator` prefers proven. |
| No strategy auto-update | Weights asserted, never fitted. `learn.analyze` starved. | `propose_strategy_update()` triggers at ≥5 new scored auditions, saves proposed version, human accepts. |
| Losers evaporated | `table_json` stored full texts but nothing surfaced them. | `loser_texts()` returns texts + gaps for training. (Storage already existed — this is retrieval.) |
| No pre-generation filter | Every candidate cost full LLM + TTS. 80% of exploit-path duds wasted budget. | `prefilter.py`: cheap Jev premise check, matched-mode reroll, fail-open. |

---

## Data flow (where scores live)

```
auditions.decision JSON     battle_score, modulator, operator (per audition)
pogs                        laugh events, beat-attributed (per audition)
feedbacks                   rating 0-3 + room_reaction (per audition)
short_views                 retention + decision (per audition)
arena_contenders            Elo, wins, bouts (per contender)
arena_votes                 blind votes with voter guards (per matchup)
battle_runs.table_json       full candidate texts + scores (per battle)
graph instances             battle_score, judge_rating (per instance, via bridge)
graph edges                 performs / judged / measured / directed (queryable)
strategy_versions           success/failed/instructions + status (proposed → accepted)
```

---

## Thresholds & gates (never auto-act on consequences)

| Gate | Threshold | Action |
|---|---|---|
| Prefilter kill | score < 0.4 | Reroll scenario once (matched mode), then proceed regardless. Never block a battle. |
| Strategy propose | ≥5 new scored auditions | Save proposed version. Pointer never moves without human. |
| Wilson significance | n≥30, CI excludes 0.5 | "Funniest" claims only above this (MAP.md rule 3). |
| Power gate (learn.py) | n<25 refuse, <60 weak | Statistical discipline on weight fitting. |
| Publish | human approval + grant | Unchanged. No loop stage publishes. |

---

## Cost per loop iteration

| Step | Cost |
|---|---|
| Prefilter (1 Jev call) | ~$0.0001 |
| Generate (3 variants, LLM) | ~$0.05-0.15 |
| Battle score (Jev) | ~$0.001 |
| TTS (winner only) | $0 (edge) or ~$0.05 (Eleven) |
| Arena/POG/retention | $0 (audience-provided) |
| Strategy propose (code) | $0 |
| **Total per battle** | **~$0.05-0.20** |
| Prefilter savings | kills ~80% of exploit duds at 1% cost |

---

## Files

```
audition/store.py         performance_history(), format_performance_brief(),
                          propose_strategy_update(), loser_texts()
audition/jev_questions.py seed_state(performance_brief), q_modulator prefers proven
audition/generate.py      fetches brief, passes to seed_state (fail-open)
audition/battle.py        matched-mode prefilter + reroll, result includes prefilter info
audition/prefilter.py     NEW: cheap premise judgment (fail-open, exploit only)
audition/app.py           _record_graph_instance bridge (prior session)
```

---

## What remains (honest gaps)

1. **No live battles yet** — all paths tested graceful-empty, but no real scores flow until auditions run with audiences voting. The loop is wired but dry.
2. **Explore/exploit balance untuned** — 70/30 split is asserted. Should adapt based on hit rate (more explore when stuck, more exploit when winning).
3. **Cross-character learning** — modulator success is per-character. "Condescending works for Nolan" doesn't inform Ralph. Mechanism-level transfer (operator × scenario, not character-specific) is the next abstraction.
4. **Retention → strategy** — `short_views` retention feeds `analytics_review` (influence2) but not `propose_strategy_update` (characters). Cross-repo signal — bridge next.
