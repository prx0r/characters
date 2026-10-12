# Anger / body / voice report — `kt728_diversifying_short`

- anger windows: **0** / baseline: **78**

## Numeric delta (anger − baseline)

| dial | anger | baseline | delta |
|------|------:|---------:|------:|
| brow_mean | None | 0.1555 | None |
| brow_range | None | 0.0483 | None |
| mouth_open_max | None | 0.0493 | None |
| mouth_wide_max | None | 0.4285 | None |
| lean_x_mean | None | -0.023 | None |
| lean_x_range | None | 0.1268 | None |
| arm_open_mean | None | 0.5488 | None |
| shoulder_tilt_abs | None | 0.0999 | None |
| hand_face_right_min | None | 0.6721 | None |

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
