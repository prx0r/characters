# Anger / body / voice report — `casey_rocket_1`

- anger windows: **0** / baseline: **86**

## Numeric delta (anger − baseline)

| dial | anger | baseline | delta |
|------|------:|---------:|------:|
| brow_mean | None | 0.1661 | None |
| brow_range | None | 0.0609 | None |
| mouth_open_max | None | 0.1035 | None |
| mouth_wide_max | None | 0.3674 | None |
| lean_x_mean | None | 0.0212 | None |
| lean_x_range | None | 0.2265 | None |
| arm_open_mean | None | 0.5718 | None |
| shoulder_tilt_abs | None | 0.0591 | None |
| hand_face_right_min | None | 0.4717 | None |

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
