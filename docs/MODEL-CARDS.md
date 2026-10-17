# MODEL CARDS — Single Source of Truth

**Last verified: 2026-10-17.** Every number below was measured and reproducible.
If any other doc disagrees with this file, this file wins.

## Laugh Prediction Models

| Model | File | AUC | Train Set | Validated On | Status |
|-------|------|-----|-----------|--------------|--------|
| **Prosody200 clean** | `audition/voicelab/prosody200_clean_model.pkl` | **0.862** | 62K segments, 200 videos | GroupKFold by video (held-out) | ✅ **BEST HONEST** — no leakage |
| **SMILE text** | `audition/voicelab/unified_laugh_model.pkl` | 0.832 | 3.8K SMILE examples | SMILE test split | ⚠️ Same-distribution, real AUC 0.832 |
| **Delivery (KT)** | `audition/voicelab/delivery_aware_model.pkl` | 0.654 | 168 beats, 12 KT stems | Leave-one-comedian-out | ✅ Working — audio energy |
| **Delivery (AM)** | `audition/voicelab/am_delivery_model.pkl` | 0.564 | 5674 windows, 5 specials | GroupKFold by comedian | ✅ Working — cross-comedian |
| **Combined (ASR)** | `audition/voicelab/combined_beats_model.pkl` | 0.548 | 2998 beats, 5 AM specials | 5-fold CV | ⚠️ Weak — text features don't help |
| ~~Prosody (old)~~ | ~~prosody_laugh_model.pkl~~ | ~~1.000~~ | 20K segments | — | ❌ **LEAKED — do not use** |
| ~~Prosody200 (leaked)~~ | ~~prosody200_heldout_model.pkl~~ | ~~1.000~~ | 62K segments | — | ❌ **LEAKED — f08 had 0.68 corr** |
| **Legacy v3** | `laugh_model_v3.pkl` | 0.664 | Unknown | LOO CV | ⚠️ Legacy |
| **Legacy v5** | `laugh_model_v5.pkl` | 0.788 | Unknown | Unknown | ⚠️ Legacy |

## Crowd Physics

| Model | File | Loss Reduction | Status |
|-------|------|----------------|--------|
| **Physics (honest)** | `/home/box/comedy-audio/learned_physics.json` | **8.9%** | ✅ Working — no label leakage |
| ~~Physics (leaked)~~ | ~~same file, old weights~~ | ~~99.7%~~ | ❌ **LEAKED — jokeIntensity = beat.laugh*10** |

**Learned constants (honest):** heat=0.487, pos=-0.388, pause=0.207, recent=0.204, wps=0.156

## Laugh Types

| Artifact | File | Status |
|----------|------|--------|
| **8 types taxonomy** | `/home/box/comedy-ai/laugh-corpus/laugh_types.json` | ✅ Working — pleasantness×arousal→ADSR→Jev |
| **ADSR envelopes** | `/home/box/comedy-ai/laugh-corpus/laugh_adsr.json` | ✅ Working — from 6 CC0 clips |
| **Type model** | `audition/voicelab/laugh_type_model.pkl` | ✅ Working |

## Voice Clones (8 total)

| Character | Clone ID | Status |
|-----------|----------|--------|
| ari | `dbeb1d68566245e2b857617b830e8031` | ✅ Converged |
| casey | in `clone_ids.json` | ✅ Converged |
| pickles | in `clone_ids.json` | ✅ Converged |
| louis | in `clone_ids.json` | ✅ Formula-level |
| kam | in `clone_ids.json` | ✅ Converged |
| norm | in `clone_ids.json` | ⚠️ Calibrated, no scribe |
| will | in `clone_ids.json` | ✅ Calibrated |
| seinfeld | in `clone_ids.json` | ⚠️ 5 clips ingested, not converged |

## What "AUC" means here

- **AUC 1.000** = model sees the label in its features (leakage) — always fake
- **AUC 0.979** = excellent on same distribution, may not transfer
- **AUC 0.654** = real generalization across comedians (our best honest number)
- **AUC 0.548** = barely above random (0.5) — text features alone don't work
- **AUC < 0.5** = model is worse than random (overfitting or inverted)

## Key Finding (2026-10-17)

**Prosody200 clean model: AUROC 0.862 with held-out videos.**
- 62K segments, 200 videos, 14 clean features (removed f08 leakage)
- GroupKFold by video — no shuffle leakage
- This is the best honest number we have

**Audio energy features beat text features for laugh prediction.**
- Text-only (ASR words): AUC 0.548
- Delivery (audio energy): AUC 0.654
- Prosody200 (clean): AUC 0.862

The laugh engine needs **audio energy**, not just text.
