# Anger / body / voice report — `kt715_walking_short`

- anger windows: **0** / baseline: **59**

## Numeric delta (anger − baseline)

| dial | anger | baseline | delta |
|------|------:|---------:|------:|
| brow_mean | None | 0.1593 | None |
| brow_range | None | 0.0447 | None |
| mouth_open_max | None | 0.0701 | None |
| mouth_wide_max | None | 0.3617 | None |
| lean_x_mean | None | 0.0228 | None |
| lean_x_range | None | 0.1323 | None |
| arm_open_mean | None | 0.5897 | None |
| shoulder_tilt_abs | None | 0.0637 | None |
| hand_face_right_min | None | 0.6187 | None |

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
