# Anger as performance — Ari Matti body + voice hypotheses

Sources: MediaPipe numeric windows (local) × qwen-plus-character theory tags.
Omni visual/vocal passes blocked (403 AccessDenied.Unpurchased) until free quota enabled.

## Per-set findings

### KT #704
- dominant emotion: **gleeful** (0.8)
- operators: ['double_interpret', 'literalize', 'garden_path', 'status_reversal']
- energy arc: cold_then_hot
- anger present: **False**
- peak body windows (mouth_wide + brow_range + lean_range):
  - t=1.0s  brow=0.455 mouthW=0.5712 leanR=0.0479 arm=0.6265 handFace=0.6099
  - t=20.0s  brow=0.2077 mouthW=0.3271 leanR=0.3858 arm=0.5737 handFace=0.8198
  - t=51.0s  brow=0.1766 mouthW=0.3563 leanR=0.2115 arm=0.6168 handFace=0.4905

### KT #715
- dominant emotion: **deadpan** (0.3)
- operators: ['literalize', 'double_interpret']
- energy arc: flat_build
- anger present: **False**
- peak body windows (mouth_wide + brow_range + lean_range):
  - t=44.0s  brow=0.1419 mouthW=0.3745 leanR=0.3572 arm=0.5753 handFace=0.4985
  - t=45.0s  brow=0.1178 mouthW=0.3887 leanR=0.2935 arm=0.7173 handFace=0.7976
  - t=48.0s  brow=0.1898 mouthW=0.3435 leanR=0.3493 arm=0.6886 handFace=0.7613

### KT #728
- dominant emotion: **deadpan** (0.6)
- operators: ['double_interpret', 'literalize', 'status_reversal']
- energy arc: flat_build
- anger present: **True**
- anger type: `mock_indignant`
- body hypotheses: ['Crossed arms during feminist setup', 'Aggressive pointing during Garfield closer']
- vocal hypotheses: ['Pitching voice up to mock activists', 'Dropping to harsh, blunt tone for the insult']
- contrast: The anger is entirely performative, serving as a vehicle for edgy observational humor rather than genuine outrage.
- peak body windows (mouth_wide + brow_range + lean_range):
  - t=31.0s  brow=0.1336 mouthW=0.4665 leanR=0.1198 arm=0.6747 handFace=1.1876
  - t=29.0s  brow=0.1331 mouthW=0.5019 leanR=0.1329 arm=0.4453 handFace=0.4358
  - t=15.0s  brow=0.1589 mouthW=0.4456 leanR=0.1935 arm=0.4936 handFace=0.3833

## Working model: what 'angry' means on stage (for rigging)

| Channel | Hot anger | Cold / mock anger | Mapping to Ralph rig |
|---------|-----------|-------------------|----------------------|
| Brow | furrow (bs_browDown↑, brow_mean↓) | flat / one raised | `annoyed` / `suspicious` |
| Mouth | wide + open (mouth_wide↑, jawOpen↑) | thin press (mouthPress↑) | `annoyed` thin vs open shock |
| Lean | forward spike (lean_x_range↑) | pull back (lean_x↓) | `lean_forward` vs hold still |
| Arms | open then point (arm_open↑ then↓) | cross / freeze | `small_shrug` vs hold still |
| Hand-face | mic hand to face (hand_face↓) | avoid | suit_adjust |
| Vocal (hypothesis) | pitch spike + volume | flat drop + spit_out | speech.emphasis↑ pace↑ |
| After punch | release into laugh | withhold stays icy | Stage Lab hold 1200ms |

Cross-ref `audition/modulators.json` → `angry.performative`:
- emphasis_delta +0.15 ← mouth_wide / brow spikes
- gestures: sharp ← lean_x_range velocity
- pace_delta +0.1 ← vocal pace (pending Omni)
- pause_mult 0.7 ← shorter gaps until punch, then hold

## Next: enable free quota
Console → Singapore free-quota → enable Free Quota Only for:
`qwen3.8-omni-flash`, `qwen3.8-flash`, `qwen-vl-*`.
Then re-run `theory/extract_performance.py <short.mp4>` without --skip-omni
to fill vocal_specific + visual anger signatures and true word-level alignment.
