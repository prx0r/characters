# Anger / body / voice report — `sir_winston_pickles_1`

- anger windows: **0** / baseline: **0**

## Numeric delta (anger − baseline)

| dial | anger | baseline | delta |
|------|------:|---------:|------:|
| brow_mean | None | None | None |
| brow_range | None | None | None |
| mouth_open_max | None | None | None |
| mouth_wide_max | None | None | None |
| lean_x_mean | None | None | None |
| lean_x_range | None | None | None |
| arm_open_mean | None | None | None |
| shoulder_tilt_abs | None | None | None |
| hand_face_right_min | None | None | None |

## Visual signature
```json
null
```

## Vocal anger_specific
```json
null
```

## Modulator cross-ref
Map deltas onto audition/modulators.json `angry.performative`:
- `emphasis_delta` ← mouth_wide_max / brow_range spikes
- `gestures: sharp` ← lean_x_range + arm_open velocity
- `pace_delta` ← vocal pace_wpm_est vs baseline
- `pause_mult` ← held_silence / breath_pattern markers
