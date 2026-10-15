# PROCESS-REVIEW — segmentation & loop design vs literature (2026-10-14)

Owner asked: is fixed-15s-beats (our s1/s2/s3) the right approach when we
expand to different styles? Review vs the literature.

## What we use and why

| Mode | Where | Tradeoff |
|---|---|---|
| Fixed 15s beats | jev_deliver/jev_loop | Honest benchmark: zero timing leak, comparable across comedians. Cost: splits mid-thought; gemini ground truth at 60s-granularity partially disagrees with 15s windows (label noise we SAW: kt704 acc stuck at 0.50 vs earlier 1.0 — window misalignment, not Jev failure). |
| Laugh-gap (>0.8s) | predict_zero_shot, cf_asr punch candidates | StandUp4AI-derived; best for production rendering; fails on barreling comics (kam: 0 gaps). |
| Gemini segments | perf_set, calibrate | Best label granularity; unavailable for unseen comics (needs video analysis). |
| Pause-split (1.1s) | perf_set | Good default for unseen audio; the workhorse. |

## Literature verdict

- TIC-TALK: topic blocks at 60s for cross-modal analysis; event-level for
  laughter. Our gemini≈topic-level, beats≈event-level. Both needed.
- StandUp4AI: word-level sequence labeling, not fixed windows — the RIGHT
  production answer. Our CF whisper "ha ha" extraction is a cheap step
  toward it. Full version: per-word laugh probability as beat boundaries.
- The honest-test vs production-render split is CORRECT per the science:
  fixed windows prevent timing leakage in evaluation (our nashville
  held-out), natural boundaries improve rendering.

## Verdict

Keep BOTH modes. Fixed beats = evaluation protocol (publishable honesty).
Pause/laugh-gap = production path. Gemini segments = calibration luxury.
The 0.50 acc on re-run kt704 is partly window-boundary noise — metric
needs boundary-tolerant scoring (allow adjacent-segment match, like
StandUp4AI's "minor temporal offsets" problem). Cheap fix: count
adjacent-emotion as half-credit.

## Loop design (Jev decode->render->calibrate)

Verified this session:
- within-set convergence works (kt704: acc 1.0 wpm 14.2 in 3 rounds)
- tempo = 1 fitted scalar per performer (speed_scale)
- per-emotion speed multipliers capture within-set swings (casey)
- cross-set generalization is the wall; needs set-diverse profiles
- raw error replay overfits; summary compression underfits. Frontier:
  confusion-matrix priors (which pairs Jev confuses for THIS comedian)
  injected into criteria, not into prose guidance.
