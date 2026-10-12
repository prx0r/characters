# Ari Matti — Kill Tony set reference (emotion-alignment targets)

Stage persona only. No biographical claims. Transcripts © their performers —
this file stores refs, metadata and ≤7-word fingerprints, never verbatim lines
(repo import rule: `SPEC-character-graph.md` §Import rules).

Persona: `theory/killtony-personas/ari_matti.json` (4 sets, mean crowd 4.0/roaring).
Lean: double_interpret, literalize, repeat_variation. Estonian immigrant material.

## Sets in this repo

| File | Episode | Date | Set at | Crowd / praise | n_beats |
|---|---|---|---|---|---|
| `killtony-minutes/ari_matti-1.json` | #704 — 2024 HEB Arena (Day One) | 2024-12-30 | 120:11 | roaring 4 / 5 | 15 |
| `killtony-minutes/ari_matti-13.json` | #706 — 2025 NYE HEB Arena | 2024-12-31 | 171:08 | roaring 4 / 5 | — |
| `killtony-minutes/ari_matty-2.json` | #715 — Kid Rock + Mark Normand | 2025-04-04 | 92:38 | roaring 4 / 5 | — |
| `killtony-minutes/ari_matti-10.json` | #725 — Matt Rife + Tony Caruso (Adam Ray) | 2025-04-05 | 27:49 | roaring 4 / 5 | — |
| `killtony-minutes/ari_matti-3.json` | #728 — Greg Fitzsimmons (rec. 2025-07-07) | 2025-07 | timestamp TBD | roaring 4 / 5 | — |

Sources: killtonydb.com/people/ari-matti (set timestamps), Spotify (ep728 rec. date).
All five are roaring/5 — ideal positive examples for granular emotion→reaction pairs.
Note: `ari_matty-2` spelling variant = same performer.

## Jev mechanism notes (hypotheses, not verdicts)

Consistent across sets: self_awareness yes, specificity yes; identity_contradiction
uncertain; displacement no. #704 adds status_reversal. See per-file `mechanisms[]`.

## Transcript slots (MISSING — fill from YouTube, keep local)

Blocked: YouTube bot-checks `yt-dlp` on this box (cookies stale). Fill per set:

```bash
# one 90s audio clip per set (set timestamp minus ~30s interview lead)
yt-dlp --cookies /root/cookies.txt --extract-audio --audio-format wav \
  --download-sections "*120:11-121:41" \
  "https://www.youtube.com/<ep704-video-id>" -o ari_matti_ep704.wav
```

Then: Qwen ASR word timing + `qwen3.8-omni-flash` vocal-emotion caption +
align to `trajectory.beats[]`. Store audio + alignment in
`/tmp/opencode/` or gitignored lab dir — NOT in git (rights + size).

Transcript status:

- [ ] ep704 @120:11 — MISSING
- [ ] ep706 @171:08 — MISSING
- [ ] ep715 @92:38 — MISSING
- [ ] ep725 @27:49 — MISSING
- [ ] ep728 @TBD — MISSING (confirm timestamp on killtonydb first)
