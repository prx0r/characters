# Anger / body / voice report — `kt704_ari_passport`

- anger windows: **0** / baseline: **55**

## Numeric delta (anger − baseline)

| dial | anger | baseline | delta |
|------|------:|---------:|------:|
| brow_mean | None | 0.1697 | None |
| brow_range | None | 0.0595 | None |
| mouth_open_max | None | 0.1021 | None |
| mouth_wide_max | None | 0.3568 | None |
| lean_x_mean | None | 0.0368 | None |
| lean_x_range | None | 0.0964 | None |
| arm_open_mean | None | 0.5657 | None |
| shoulder_tilt_abs | None | 0.0556 | None |
| hand_face_right_min | None | 0.7512 | None |

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
