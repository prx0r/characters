# Kaggle datasets (downloaded 2026-10-16, user priortrades)

Token: `~/.kaggle/access_token` (KGAT, 600). Client: repo `.venv` kaggle 2.2.4.
Re-download: `KAGGLE_API_TOKEN=$(cat ~/.kaggle/access_token) .venv/bin/kaggle datasets download -d <ref> -p theory/datasets/<dir> --force`

## 1. ali-wong/ — thedevastator/ali-wong-comedy-captions-and-topics (34KB)

925 timed captions (0:00:28–~58:00, mean line 2.9s), **352 with laugh score
0–10** (half-steps; 160 rows ≥2.0), 120 topic groups (6-getting older,
32-hpv…) with hierarchy levels 1–6 and 3 marked callbacks.

**Maps to our shape:** `caption`+`timeStart/timeStop` ≈ scribe word windows;
`laugh` ≈ POG strength (continuous, finer than crowd_ord 0–4); `group` ≈
beat segments in delivery.json; `topics.level` ≈ bit nesting; `callback`
column ≈ our threads/running-gag field. Pre-labelled end-to-end example of
what a full character set *should* look like after extraction.

## 2. prosody200/ — subhajitdas/top200-youtube-comedy-prosody (6.7MB, CC-BY-4.0)

62,042 segments × 15-dim float32 (F0 mean/std, energy, MFCCs, spectral —
means ≈ [0.03, 0.06, … 960Hz F0, 1825 spectral, …]) from 200 YouTube comedy
videos. Labels: 16.85% positive (laughter segment). Per-video laugh rate
p10 0.09 → p90 0.34. Keys: `features`, `labels`, `vids` (11-char video id).

**Maps to:** train the laugh-position predictor (audio-only v1). Features
align with `theory/acoustic.py` output (F0/energy/MFCC) — same family, can
fine-tune on their labels then apply to our wavs. Feeds anticipatory-laugh
curve + stay-in-the-bit detectors (see louistheory1.md). CC-BY-4.0: credit
required in any published model/product.

## 3. comedians-transcript/ — abhinandansharma19/comedians-transcript (849KB)

20 comedians (adam, andrew, dave, drew, eric,gary, iliza, john, maria,
marlon, mike, neal, patton, pete, ricky, shane, tig, tom, trevor, vir —
Berg/Dave Chappelle/… first names; ~39KB transcript each, total ~775KB).
Pickles: `corpus.pkl` (transcript+full_name), `data_clean.pkl` (indexed by
first name), `dtm.pkl` (20×10005 count matrix, sklearn 1.2 vintage —
unpickle warns on 1.9), `cv.pkl` CountVectorizer.

**Maps to:** GTVH pre-label corpus (`audition/gtvh.py` operators against 20
full sets). Lexical baseline vs our Jev noul tags — do rule features on
these transcripts predict the same primary mechanisms Jev picks on KT?
Also seed vectors for the comedian-persona work (`kt_personas`).

## Where they hook in (next runs)

| Dataset | First run | Cost |
|---|---|---|
| ali-wong | sanity-check laugh-curve metric: does anticipatory-laugh shape predict laugh≥2 rows? | free, local |
| prosody200 | train logistic laugh segmenter on 62K, eval AUC; export weights for acoustic.py pipeline | free, CPU |
| comedians-transcript | run gtvh.py + kt_decode segment() over 20 sets, diff vs Jev primary on any overlapping comedians | free |

Licenses: prosody200 CC-BY-4.0 (credit). Ali Wong = derived from Netflix
specials — captions are fair-use research here; do **not** ship the caption
text in products. Comedians-transcript: no explicit license on Kaggle page —
treat as research-only until clarified.
