# Delivery Review — Comedian Profile → Directed Fish TTS Audio

**Goal:** Take a comedian's profile (style, voice, delivery patterns) + their minute text → render Fish TTS audio that sounds like them performing it.

**Status:** Partially working. Louis formula-level. Ari/casey/pickles/kam converged at knob level. Norm/seinfeld not calibrated.

---

## What We Know (Measured)

### Louis CK Formula (13 clips, verified)
- **Pauses:** 1.67s average (pros 1.39, amateurs 0.96)
- **Pace:** 3.94 syll/s, 163 wpm (slower than pros)
- **Dynamics:** 19.6 dB (very low — close-mic intimacy)
- **Pitch:** std 6.83 semitones
- **Centroid:** 1535 Hz (dark/warm)
- **Technique mix:** literalize 24%, escalation 19%, self_deprecation 16%, audience_address 13%
- **Pause ladder:** setup 0.6s → pre-punch 1.5s → tag 1.0s ±25% jitter
- **Coupling:** pros extend pause before surprise 41.2% vs amateurs 27.4%

### KT Calibration (converged states)
| Performer | Emotion Acc | WPM MAE | Var MAE | Status |
|-----------|-------------|---------|---------|--------|
| ari | ≥0.60 | ≤20 | ≤1.5 | Converged at knobs |
| casey | 1.0 | 26.1 | 0.63 | 2/3 bounds met |
| pickles | — | 18.7 | 0.94 | Converged with clone voice |
| kam | — | 33.6 | — | Partial (persona prior) |
| louis | 0.19 | 37.6 | — | Formula-level only |
| norm | — | — | — | Not calibrated |
| seinfeld | — | — | — | Not calibrated |

### Delivery Features That Matter
1. **Energy variation** (e_std) — strongest laugh predictor (AUC 0.654)
2. **Pause before punchline** — dpv coupling ratio (pros +41%)
3. **WPM** — per-comedian baseline (Louis 163, Ari 282)
4. **Pitch std** — emotion channel (deadpan low, manic high)
5. **Dynamics** — intimacy vs roast (Louis 19.6 dB, roast 51 dB)

---

## What's Broken

1. **Pitch not in any training row** — measured everywhere, used nowhere
2. **Spectral features unused** — centroid, MFCCs extracted but not modeled
3. **dpv coupling ratio not a feature** — only raw pause_before
4. **Laugh onset timing not modeled** — 78% of laughs start before punchline ends
5. **Technique tags not in delivery path** — 10 Jev mechanisms exist but not merged
6. **voice_engine.json never generated** — converged states not reusable
7. **Per-comedian thresholds hand-tuned** — not learned
8. **kt_archive_graph unused** — 569 sets, 408 comedians, zero training
9. **Realtime engine approximates features** — 8/14 dims are zeros
10. **No word-level alignment** — fixed 6s/15s windows miss punchline timing

---

## 10 Todos

### T1: Build voice_engine.json from converged states
Merge ari/casey/pickles/kam calibration into one reusable profile file.
```json
{
  "ari": {"speed_scale": 1.565, "wpm_target": 289, "pitch_std": 4.8, "dynamics_db": 42},
  "louis": {"pause_ladder": [0.6, 1.5, 1.0], "wpm": 163, "dynamics_db": 19.6}
}
```
**Effort:** 30min. **Impact:** Makes converged states reusable.

### T2: Add pitch + spectral features to delivery training
Extract F0 std, centroid, MFCCs from audio → add to beat rows → retrain.
Currently: `laugh_predictor` uses wps/pause/pos/hist only.
Fix: merge `librosa_features.json` + `acoustic.py` output into training rows.
**Effort:** 1hr. **Impact:** Should push AUC 0.654 → 0.75+.

### T3: Train on kt_archive_graph (569 sets)
Use crowd reactions (roaring/big/moderate/light/silence) as labels.
Features: comedian ID, topics, position, word count → crowd_ord prediction.
**Effort:** 1hr. **Impact:** Cold-start priors for unseen comedians.

### T4: Implement dpv coupling ratio as feature
`coupling = pause_before_surprise / baseline_pause`
Pros: 1.41, amateurs: 1.27. This is the expertise signal.
**Effort:** 30min. **Impact:** Better timing prediction.

### T5: Word-level laugh alignment (StandUp4AI method)
Replace fixed 6s windows with word-level timestamps.
Label each word: laugh_near True/False.
Download StandUp4AI full dataset (330h, 130K labels).
**Effort:** 2hr. **Impact:** Fixes window misalignment (kt704 acc stuck at 0.50).

### T6: Calibrate norm + seinfeld
Run jev_loop on norm_sets/ and seinfeld clips.
Get them to converged state (acc≥0.6, wpm≤20, var≤1.5).
**Effort:** 2hr. **Impact:** Completes priority lane (stand-still comics).

### T7: Laugh onset regression (not just binary)
Predict: (a) will they laugh, (b) WHEN (delay in ms), (c) HOW LONG.
Casey corpus: median delay −0.36s (anticipatory), 78% overlap.
**Effort:** 1hr. **Impact:** Natural laughter timing in renders.

### T8: Realtime engine proper feature extraction
Replace 8 zero-placeholders with real F0/MFCC/energy extraction.
Use librosa or pyloudnorm in the audio callback path.
**Effort:** 1hr. **Impact:** Realtime model actually works.

### T9: Technique tags → delivery recipe mapping
10 Jev mechanisms × 8 emotions → Fish TTS direction strings.
garden_path + deadpan → `[pause] [dry] ... [surprise]`
escalation + manic → `[faster] [excited] ... [explosive]`
**Effort:** 1hr. **Impact:** Semantic-aware delivery.

### T10: End-to-end test: Louis minute → directed render
Take a Louis CK minute text → apply his formula (pauses, pace, dynamics) →
render with Fish TTS → measure wpm/pitch/dynamics vs actual Louis audio.
Target: wpm_mae ≤20, var_mae ≤1.5.
**Effort:** 1hr. **Impact:** Proves the pipeline works.

---

## Priority Order

1. **T1** (voice_engine.json) — unlocks reusability
2. **T2** (pitch features) — biggest model improvement
3. **T10** (end-to-end test) — proves the pipeline
4. **T4** (dpv coupling) — expertise signal
5. **T3** (kt_archive) — cold-start priors
6. **T9** (technique → recipe) — semantic delivery
7. **T5** (word-level) — fixes alignment
8. **T7** (onset regression) — natural timing
9. **T6** (norm/seinfeld) — completes roster
10. **T8** (realtime features) — makes realtime work

---

## Key Files

| File | What |
|---|---|
| `theory/LOUIS-FORMULA.md` | Measured Louis delivery |
| `theory/LOUIS-JOKE-ANATOMY.md` | Word-granularity joke structure |
| `theory/DVP-FINDINGS.md` | Pause ladder + coupling |
| `audition/jev_loop.py` | Calibration loop |
| `audition/jev_deliver.py` | 8-emotion vocab + recipes |
| `audition/voice_judge.py` | Audio measurement |
| `audition/engine_registry.py` | Roll up converged states |
| `voicelab/calibrate/*.json` | Per-performer calibration |
| `theory/kt_archive_graph.json` | 569 sets, 408 comedians |
| `theory/killtony-features.jsonl` | 276 sets with theory tags |
