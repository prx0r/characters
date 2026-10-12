# Anger / body / voice report — `casey_rocket_2`

- anger windows: **0** / baseline: **44**

## Numeric delta (anger − baseline)

| dial | anger | baseline | delta |
|------|------:|---------:|------:|
| brow_mean | None | 0.1249 | None |
| brow_range | None | 0.0732 | None |
| mouth_open_max | None | 0.1062 | None |
| mouth_wide_max | None | 0.3646 | None |
| lean_x_mean | None | -0.0447 | None |
| lean_x_range | None | 0.2368 | None |
| arm_open_mean | None | 0.5275 | None |
| shoulder_tilt_abs | None | 0.0491 | None |
| hand_face_right_min | None | 0.434 | None |

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
