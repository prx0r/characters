# MODEL REVIEW — Complete Inventory (2026-10-17)

**Every model trained in this repo. Verified by loading each pickle.**

## Summary

- **24 models total**
- **2 trustworthy audio models** (prosody200_clean 0.862, delivery_aware 0.654)
- **3 leaked models** (prosody200_heldout, prosody_laugh, laugh_model_v1)
- **4 broken models** (delivery_enhanced 0.474, laugh_model_v4 0.477, laugh_type 0.376, calibrated_ensemble 0.530)
- **15 legacy/superseded models**
- **Most models have no committed training script** — only pickles survive

## AUDIO MODELS (the ones you want)

| Model | AUC | Features | Data | Validation | Status |
|-------|-----|----------|------|------------|--------|
| **prosody200_clean** | **0.862** | 14 prosody features (f0, energy, MFCC, spectral) | 62K segments, 200 videos | GroupKFold by video | ✅ **BEST — use this** |
| **delivery_aware** | **0.654** | pos, dur, pause, wps, energy_mean/std | 168 KT beats, 5 comedians | Leave-one-comedian-out | ✅ **Best cross-comedian** |
| am_delivery | 0.551 | pos, energy_mean/std/max/min, n_pauses | 5674 windows, 3 comedians | GroupKFold by comedian | ✅ Honest but weak |
| delivery_enhanced | 0.474 | timing + f0, centroid, MFCC, onset | 185 KT beats | GroupKFold | ❌ Below random |
| prosody200_heldout | 1.000 | all 15 features (incl. leaky f08) | same as prosody200 | GroupKFold | ❌ **LEAKED** |
| prosody_laugh | 1.000 | 15 features | 20K segments | unknown | ❌ **LEAKED** |

**Audio model verdict:** prosody200_clean (0.862) is the only strong audio model. It uses precomputed Kaggle features that don't match our realtime extractor. delivery_aware (0.654) uses RMS energy that DOES match our extractor.

## TEXT MODELS

| Model | AUC | Features | Data | Validation | Status |
|-------|-----|----------|------|------------|--------|
| smile | 0.979 | 11 lexical + 1000 TF-IDF | SMILE-Next 3.8K | same-distribution | ⚠️ Same-dist only |
| unified | 0.832 | 11 lexical + 1000 TF-IDF | SMILE-family | same-distribution | ✅ Canonical text |
| laugh_model_v5 | 0.788 | 609 TF-IDF + 5 state | Ali Wong + KT | unknown | ⚠️ Suspect leakage |
| laugh_type | 0.376 | 8 lexical + 500 TF-IDF | unknown | unknown | ❌ Barely beats chance |
| word_level | 0.560 | pause_after, pos, timing | StandUp4AI 3.2K words | GroupKFold by video | ⚠️ Weak but honest |

**Text model verdict:** smile (0.979) works on SMILE test split but doesn't transfer. unified (0.832) is the canonical text model. Neither predicts laughter on real standup.

## TIMING-ONLY MODELS

| Model | AUC | Features | Data | Status |
|-------|-----|----------|------|--------|
| laugh_model_v3 | 0.664 | wps, pause, dur, pos, hist | KT sets | ⚠️ Shuffled CV (leakage) |
| laugh_model_v2 | 0.651 | 8 features | Casey riffs | ⚠️ Legacy |
| laugh_model_v4 | 0.477 | 5 features | 104 beats | ❌ Below random |
| combined_beats | 0.572 | wps, pause, dur, pos, hist | 2998 AM beats | ⚠️ Misnamed (no text used) |
| laugh_track | — | wps, pause, dur, pos, hist | unknown | ⚠️ Legacy |

**Timing model verdict:** All timing-only models are weak (0.48-0.66). The shuffled CV in v3 inflates the score.

## ENSEMBLE

| Model | AUC | Components | Calibration | Status |
|-------|-----|------------|-------------|--------|
| calibrated_ensemble | 0.530 | word_level + delivery + free_energy + crowd_state + lexical | meta-LR on 5702 events | ❌ Delivery dominates (0.727), rest add nothing |

**Ensemble verdict:** Doesn't help. Delivery is the only real signal.

## WHAT'S ACTUALLY HAPPENING

**The audio path works:**
1. prosody200_clean: 0.862 (but features don't match our extractor)
2. delivery_aware: 0.654 (features DO match our extractor)
3. Both use GroupKFold by video/comedian (no shuffle leakage)

**The text path doesn't transfer:**
1. SMILE 0.979 → real standup: barely above random
2. Text features don't predict laughter cross-comedian

**The gap:** prosody200 uses 14 precomputed features we can't compute in realtime. delivery_aware uses RMS energy we CAN compute. The missing features are: F0 (pitch), MFCCs, spectral centroid.

## THE REAL AUDIO MODEL WE NEED

Train on prosody200 features but compute them ourselves:
1. Extract F0, energy, MFCC, spectral from audio (librosa)
2. Match the 14-feature format of prosody200
3. Train on our 5 AM specials with AM laugh events
4. Validate with GroupKFold by comedian
5. Target: AUC 0.75+ (between our 0.654 and prosody200's 0.862)

This is the audio model that would actually work in production.

## KEY DISCREPANCIES FIXED

1. MODEL-CARDS.md claimed unified = 0.979 → real is 0.832
2. MANIFEST said delivery_aware = 103 beats → real is 168 beats, AUC 0.654
3. combined_beats claimed "text features don't help" → text was never used
4. laugh_model_v4 claimed 0.629 → pickle stores 0.477
5. laugh_predictor_v3 prints "LOO-CV" → actually StratifiedKFold shuffle
