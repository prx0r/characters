# ATTARDO-TIMING-MAP — ch10/GTVH claim → engine knob (attardo.timing.v1)

Source graph: `gcomedy/library/comedy/attardo-graph/graph.json` (76 nodes,
117 edges, Attardo, *The Linguistics of Humor*, OUP 2020). Chapter 10 =
The Performance of Humor. KR-NS (Narrative Strategy, ch7 p171) is the GTVH
knowledge resource that IS delivery: "how the joke is told". Edges:
KR-NS → implements → release-theory; KR-NS → maps_to → timing-performance.

**Thesis:** NS is 1/6th of the joke (GTVH). `delivery.style` plays NS while
LA stays verbatim. This mapping table is the contract between theory and
`delivery_engine.py` — every claim has a knob or is marked NOT-A-KNOB.

## The mapping

| # | Claim (source) | Engine knob | State |
|---|---|---|---|
| T1 | Punchlines preceded by substantial pauses, **0.6s floor** (Attardo ch10 p232; H1 = 14x baseline) | `pause_ladder[1]` (pre_punch) × `coupling_ratio`, enforced floor 0.6s in `assign_timings` | gap → fix 3 |
| T2 | Release theory: pause accumulates tension, punch releases; NS timing IS the release mechanism (graph edge KR-NS→release-theory) | hold-before (T1) + **resolution window after punch** (`pause_after`) | gap → fix 3 |
| T3 | **Norrick: punchlines faster than setup** ("more rapid, fluid delivery", p232) | per-beat speed contrast: setup/tag base, punch ×1.08, escalation/list ×1.15 → outside clean zone decomposed by `tempo_via_prompt` (direction language, owner rule) | gap → fix 5 |
| T4 | **Resume after laughter** — when to re-enter (p232) + audience as co-performer (p245): laughter SHAPES timing | `p_laugh` scales `pause_after` (predicted laugh → longer window; crowd_state loop already modulates p_laugh) | gap → fix 7 |
| T5 | **Prosody carries the frame** (p228): pitch marks incongruity, stress highlights switch word, voice quality signals frame shift | style `emotion_cues`/`emotion_forbidden` (frame vocabulary) + `[emphasis]` on punch last word (fish_tts.render_beat) + style `pitch_std_st`/`dynamics_db` conformance targets | partial: cues wired; emphasis + volume → fix 4 |
| T6 | Flat delivery + long holds = tension engine (release needs accumulation; deadpan = flouting manner maxim, Logi 2025) | style `volume_db` (Norm −3.3) → fish `prosody.volume`; low `temperature`; forbidden high-energy cues | gap → fix 4 |
| T7 | **Performance ≠ competence** (ch10): same text, different result | text gates (slop/jev) = competence; `delivery_style` + conformance = performance — kept separate by design | done (SDK) |
| T8 | Jab lines within body (Attardo 2001, p175), not only end punch | beat types already include tag/closer; `tag_mechanism` marks jab-like short beats — timing ladder applies per beat type | done |
| T9 | Gesture: body-in-rhythm (Carlin, p240), stillness before punch (TIC-TALK r=−0.75) | NOT audio knob — `actions`/`profile.gesture_frequency` (visual layer); engine only holds audio still (T1) | not-a-knob (visual) |
| T10 | Social context: venue/culture/genre shapes rhythm (ch10) | NOT wired — future style field `context` (club/theater); out of scope now | not-a-knob |
| T11 | Audience feedback loop essential (p245); "stay in the bit" | `crowd_state.CrowdStateMachine` already persists heat/momentum across beats; live POG loop = future (comedy-room) | partial (predicted only) |
| T12 | Louis ladder measured: setup .6 / pre-punch 1.5 / tag 1.0 ±25%, coupling 1.41 (pros 41.2% vs amateurs 27.4% extend pre-surprise pause) | `pause_ladder` + `pause_jitter` in `delivery_style.v1` (harvested per comedian) | done (style_harvest, louis self-test PASS) |

## Beat timing layout (after fix 3)

```
beat i:  [pause_before(i)] [audio(i)] [pause_after(i)]
                                   ^
punchline(i): pause_before = ladder[1] × coupling (T1, floor 0.6)
punchline(i): pause_after  = post_punch_s × laugh scale (T2, T4)
setup(i):     pause_before = ladder[0] × jitter;  pause_after ≈ 0
tag(i):       pause_before = ladder[2] × jitter;  pause_after = small
closer:       pause_before = ladder[0] × 1.5
```

`post_punch_s` (style): from laugh react latencies when scribe has anchors
(`react_median_s`), else ladder[2]; Buddha override floor 1.0s (silence
after punch — his spec: "don't step on the laugh").

## Speed layout (after fix 5)

```
desired = profile.speed_scale × beat_factor
  setup/opener: ×1.0      punchline: ×1.08 (snap, T3)
  tag: ×1.05              escalation/list mechanism: ×1.15 (inventory accelerate, T3)
  closer: ×0.95
If desired outside 0.92–1.08 → fish_tts.tempo_via_prompt decomposes into
emotion-cue intrinsic tempo + tone marker; the API speed knob never leaves
the clean zone (HANDOVER rule 2).
Verdict stop: punchline speed target does NOT ramp — the contrast IS the
stop (lists ran hot into it).
```

## Buddha instantiation (derived, not invented — owner 2026-10-21)

| Spec line | Knob |
|---|---|
| pause 1.5–3s before every punch (0.6s floor, Louis 1.67, Buddha longer) | `overrides.punchline_hold_ms: 1500` → ladder[1] = 1.5 (jitter ±25% → 1.5–1.9; stillness is his frame) |
| flat energy throughout (0.4), important words unstressed | style volume −3.3dB, forbidden `[excited]`/`[happy]`/`[manic]`, temp 0.5, no `[emphasis]` on deadpan mechanism beats |
| lists accelerate, verdicts stop dead | fix 5 contrast (escalation ×1.15, punch ×1.08 snap-to-hold) |
| refrains identical, never varied | text-level rule (material); engine renders refrain beats with same cue+temp (already deterministic seed 42) |
| silence after the punch; room retunes next pause | `post_punch_s` + p_laugh scale (fixes 3+7) |

## Honesty notes
- Conformance ≠ funny (repo rule): this map makes renders MECHANICALLY
  faithful to measured human delivery; humans dispose.
- T9/T10 deliberately not knobs — visual/context layers, not audio.
- Graph nodes KR-NS/prosody/performance-of-humor had empty
  `our_operators` — this file + `delivery.style` are their operator
  mapping (gcomedy graph updated locally, not pushed).
